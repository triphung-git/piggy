// GitHub Release mutations are confined to jobs with contents:write permission.
async function assertTag({github, context}, tag, sha) {
  const repository = {owner: context.repo.owner, repo: context.repo.repo};
  let object = (await github.rest.git.getRef({...repository, ref: `tags/${tag}`})).data.object;
  for (let depth = 0; object.type === 'tag' && depth < 10; depth++) {
    object = (await github.rest.git.getTag({...repository, tag_sha: object.sha})).data.object;
  }
  if (object.type !== 'commit' || object.sha !== sha) throw new Error('Release tag moved after validation; publication blocked');
}

async function createDraft({github, context, core}) {
  const {RELEASE_TAG: tag, RELEASE_SHA: sha, RELEASE_PRERELEASE: prerelease} = process.env;
  const repository = {owner: context.repo.owner, repo: context.repo.repo};
  await assertTag({github, context}, tag, sha);
  const marker = `<!-- release-sha: ${sha} -->`;
  let release;
  try {
    release = (await github.rest.repos.getReleaseByTag({...repository, tag})).data;
  } catch (error) {
    if (error.status !== 404) throw error;
  }
  if (release) {
    if (!release.draft) throw new Error('This tag is already published; use a new version instead of replacing it');
    if (!release.body?.includes(marker)) throw new Error('Existing draft belongs to a different commit or was created manually; inspect it before retrying');
  } else {
    release = (await github.rest.repos.createRelease({...repository, tag_name: tag, target_commitish: sha,
      name: `TFT Post-Match Studio ${tag}`, body: `${marker}\nInstallers for Windows, macOS and Linux.`,
      draft: true, prerelease: prerelease === 'true'})).data;
  }
  core.setOutput('id', String(release.id));
}

async function publishDraft({github, context}) {
  const {RELEASE_TAG: tag, RELEASE_SHA: sha, RELEASE_ID: releaseId, RELEASE_PRERELEASE: prerelease} = process.env;
  const repository = {owner: context.repo.owner, repo: context.repo.repo};
  await assertTag({github, context}, tag, sha);
  const release_id = Number(releaseId);
  if (!Number.isSafeInteger(release_id) || release_id <= 0) throw new Error('Invalid draft release ID');
  const release = (await github.rest.repos.getRelease({...repository, release_id})).data;
  if (!release.draft || release.tag_name !== tag || !release.body?.includes(`<!-- release-sha: ${sha} -->`)) {
    throw new Error('Draft state changed; publication blocked');
  }
  const assets = await github.paginate(github.rest.repos.listReleaseAssets, {...repository, release_id, per_page: 100});
  if (!assets.some(asset => asset.name === 'latest.json' && asset.size > 0)) throw new Error('Verified updater manifest is missing');
  if (!assets.some(asset => asset.name === 'SHA256SUMS' && asset.size > 0)) throw new Error('Verified SHA256 checksums file is missing');
  await github.rest.repos.updateRelease({...repository, release_id, draft: false, prerelease: prerelease === 'true',
    make_latest: prerelease === 'true' ? 'false' : 'legacy'});

}

module.exports = {assertTag, createDraft, publishDraft};
