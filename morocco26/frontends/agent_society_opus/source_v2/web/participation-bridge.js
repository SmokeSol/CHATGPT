/* ATLAS // compatibility bridge for live LLM contributions.
   Supports both the legacy static-file claim and the current inline payload.
   It intentionally does not expose credentials or collective results. */
'use strict';

(function () {
  if (typeof window.claimContribution !== 'function') return;

  window.claimContribution = function claimContribution(provider) {
    var choices = typeof reader$ === 'function' ? reader$('.assistant-choices') : null;
    if (choices) choices.classList.add('busy');

    fetch(READER_API + '/claim', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({provider: provider})
    }).then(function (r) {
      return r.json().then(function (j) { if (!r.ok) throw j; return j; });
    }).then(function (claim) {
      ACTIVE_CONTRIBUTION = {provider: provider, claim_token: claim.claim_token};
      localStorage.setItem('atlas-active-contribution', JSON.stringify(ACTIVE_CONTRIBUTION));

      var payloadPromise;
      if (claim.payload && claim.payload.context && claim.payload.voter_batch) {
        payloadPromise = Promise.resolve(claim.payload);
      } else if (claim.files) {
        payloadPromise = loadContributionFiles(claim.files);
      } else {
        throw new Error('CLAIM_PAYLOAD_MISSING');
      }

      return payloadPromise.then(function (payload) {
        return copyText(contributionPrompt(payload)).then(function () {
          showContributionReady(provider);
        });
      });
    }).catch(function () {
      closeModal();
      toast('L’expérience ouvre très bientôt', 'La participation n’a pas pu être préparée. Réessayez dans quelques instants.');
    });
  };
}());
